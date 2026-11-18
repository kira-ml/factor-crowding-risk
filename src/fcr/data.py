"""Data acquisition, caching, and validation.

Single responsibility: produce a validated price/volume panel. No feature logic
lives here (methodology section 1).

Downloads are cached per ticker so that a run is resumable. Yahoo rate-limits
aggressively on large batched requests, so tickers are fetched individually with
pacing and exponential backoff. This is slower than a batch call but reliable and
idempotent.
"""

from __future__ import annotations

import hashlib
import json
import time
import warnings
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .config import DATA_DIR, RAW_DIR, Config

warnings.filterwarnings("ignore", category=FutureWarning)

WIKI_PAGES = (
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (research; contact: repository owner)"}
TICKER_DIR = Path(RAW_DIR) / "tickers"


class DataError(RuntimeError):
    """Raised when a data invariant is violated."""


@dataclass
class Panel:
    """Adjusted close and share volume, daily, columns are tickers."""

    close: pd.DataFrame
    volume: pd.DataFrame

    def __post_init__(self) -> None:
        self.close = self.close.sort_index()
        self.volume = self.volume.reindex(self.close.index)
        self.close.columns = [str(c) for c in self.close.columns]
        self.volume.columns = [str(c) for c in self.volume.columns]

    @property
    def returns(self) -> pd.DataFrame:
        # Do not forward-fill prices. A stale price creates a zero return and a
        # false sense of liquidity around a halt or delisting.
        return self.close.pct_change(fill_method=None)

    @property
    def dollar_volume(self) -> pd.DataFrame:
        return self.close * self.volume

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.close.index

    def last_valid(self) -> pd.Series:
        return self.close.apply(lambda s: s.last_valid_index())

    def slice(self, end: pd.Timestamp) -> Panel:
        return Panel(self.close.loc[:end], self.volume.loc[:end])


# ---------------------------------------------------------------------------
# Tickers
# ---------------------------------------------------------------------------
def _clean_symbols(symbols: list[str]) -> list[str]:
    out: list[str] = []
    for symbol in symbols:
        symbol = str(symbol).strip().replace(".", "-")
        if not symbol or symbol.lower() == "nan":
            continue
        if not all(ch.isalnum() or ch in "-" for ch in symbol):
            continue
        out.append(symbol)
    return sorted(set(out))


def get_candidate_tickers(cfg: Config, refresh: bool = False) -> list[str]:
    """Current S&P 500 and S&P 400 members.

    The list is a candidate pool, not the investable universe. The universe rule
    is liquidity-based and point-in-time. Do not truncate the pool
    alphabetically; that would turn a data limit into a silent selection rule.
    """
    cache = Path(RAW_DIR) / "tickers.json"
    if cache.exists() and not refresh:
        cached = json.loads(cache.read_text())
        if len(cached) >= 100:
            return cached

    symbols: list[str] = []
    for url in WIKI_PAGES:
        try:
            response = requests.get(url, headers=_HEADERS, timeout=30)
            response.raise_for_status()
            tables = pd.read_html(StringIO(response.text))
        except Exception as exc:
            raise DataError(f"Could not read constituents from {url}: {exc}") from exc

        found = False
        for table in tables:
            for column in ("Symbol", "Ticker symbol", "Ticker"):
                if column in table.columns:
                    symbols.extend(table[column].astype(str).tolist())
                    found = True
                    break
            if found:
                break
        if not found:
            raise DataError(f"No symbol column found at {url}")

    tickers = _clean_symbols(symbols)
    if len(tickers) < 100:
        raise DataError(f"Candidate pool too small: {len(tickers)}")
    cache.write_text(json.dumps(tickers))
    return tickers


# ---------------------------------------------------------------------------
# Per-ticker cache
# ---------------------------------------------------------------------------
def _extract(raw: pd.DataFrame, field: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        if field in raw.columns.get_level_values(0):
            frame = raw.xs(field, axis=1, level=0)
        else:
            return pd.DataFrame()
    elif field in raw.columns:
        frame = raw[[field]].copy()
    else:
        return pd.DataFrame()
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()
    frame.columns = [str(c) for c in frame.columns]
    return frame


def _read_no_data() -> dict[str, str]:
    path = Path(RAW_DIR) / "no_data.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _write_no_data(record: dict[str, str]) -> None:
    path = Path(RAW_DIR) / "no_data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2))


def _fetch_one(ticker: str, cfg: Config, pause: float = 0.25) -> pd.DataFrame | None:
    """Fetch one ticker's full history, with retries. Returns None on no data.

    Empty responses are not written as price caches. A transient outage is
    recorded in ``no_data.json`` with a timestamp and retried after a cooldown,
    so a rate limit cannot silently remove a ticker forever.
    """
    cache = TICKER_DIR / f"{ticker}.parquet"
    if cache.exists():
        frame = pd.read_parquet(cache)
        if len(frame):
            return frame
        cache.unlink()  # legacy empty cache from the defective implementation

    no_data = _read_no_data()
    if ticker in no_data:
        try:
            age = (
                pd.Timestamp.now(tz="UTC") - pd.Timestamp(no_data[ticker])
            ).total_seconds()
        except Exception:
            age = 0
        if age < 7 * 24 * 3600:
            return None

    import yfinance as yf

    delays = [0, 8, 30, 75]
    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            raw = yf.download(
                ticker,
                start=cfg.start,
                end=cfg.end,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception:
            continue
        if raw is None or raw.empty:
            continue

        close = _extract(raw, "Close")
        volume = _extract(raw, "Volume")
        if close.empty:
            continue
        close.index = pd.to_datetime(close.index).tz_localize(None)
        volume.index = pd.to_datetime(volume.index).tz_localize(None)
        frame = pd.DataFrame(
            {
                "close": close.iloc[:, 0].astype(float),
                "volume": volume.iloc[:, 0].astype(float)
                if not volume.empty
                else np.nan,
            }
        ).sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        frame.to_parquet(cache)
        time.sleep(pause)
        return frame

    no_data[ticker] = pd.Timestamp.now(tz="UTC").isoformat()
    _write_no_data(no_data)
    raise DataError(f"Failed to fetch {ticker} after retries")


def fetch_panel(cfg: Config, force: bool = False, verbose: bool = True) -> Panel:
    TICKER_DIR.mkdir(parents=True, exist_ok=True)
    tickers = get_candidate_tickers(cfg)

    if force:
        for path in TICKER_DIR.glob("*.parquet"):
            path.unlink()
        no_data_path = Path(RAW_DIR) / "no_data.json"
        if no_data_path.exists():
            no_data_path.unlink()

    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    failures = 0
    started = time.time()

    for i, ticker in enumerate(tickers, start=1):
        try:
            frame = _fetch_one(ticker, cfg)
        except DataError:
            failures += 1
            frame = None
        if frame is not None and len(frame) > 0:
            closes[ticker] = frame["close"]
            volumes[ticker] = frame["volume"]
        if verbose and (i % 50 == 0 or i == len(tickers)):
            elapsed = time.time() - started
            print(
                f"  {i}/{len(tickers)} tickers, {len(closes)} with data, {elapsed:.0f}s"
            )

    if len(closes) < 100:
        raise DataError(f"Only {len(closes)} tickers with data; need at least 100")

    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(volumes).reindex(close.index)
    close = close.loc[:, close.notna().sum() > 0]

    panel = Panel(close.loc[cfg.start : cfg.end], volume.loc[cfg.start : cfg.end])
    validate(panel)
    if verbose:
        print(f"  panel: {panel.close.shape[0]} days x {panel.close.shape[1]} tickers")
        print(f"  range: {panel.dates[0].date()} to {panel.dates[-1].date()}")
        if failures:
            print(f"  tickers failed after retries: {failures}")
    return panel


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate(panel: Panel) -> dict:
    close = panel.close
    if not isinstance(close.index, pd.DatetimeIndex):
        raise DataError("Index is not a DatetimeIndex")
    if not close.index.is_monotonic_increasing:
        raise DataError("Index is not monotone increasing")
    if close.index.has_duplicates:
        raise DataError("Duplicate dates in index")
    if len(close) < 252:
        raise DataError(f"Insufficient history: {len(close)} rows")

    values = close.to_numpy(dtype=float)
    if np.isnan(values).all(axis=1).any():
        bad = close.index[np.isnan(values).all(axis=1)][:5]
        raise DataError(f"Dates with no prices at all: {list(bad)}")
    if np.nansum(values <= 0) > 0:
        raise DataError("Non-positive prices present")

    returns = close.pct_change(fill_method=None)
    jumps = int((returns.abs() > 0.5).to_numpy().sum())
    coverage = float(close.notna().mean().mean())
    if panel.volume is not None:
        if (panel.volume < 0).to_numpy().any():
            raise DataError("Negative volume present")
        if np.isinf(panel.volume.to_numpy(dtype=float)).any():
            raise DataError("Infinite volume present")

    return {
        "rows": len(close),
        "tickers": int(close.shape[1]),
        "coverage": round(coverage, 4),
        "large_moves": jumps,
        "start": str(close.index[0].date()),
        "end": str(close.index[-1].date()),
    }


def panel_hash(panel: Panel) -> str:
    """Stable content hash of the cached panel, recorded in the manifest."""
    digest = hashlib.sha256()
    for frame in (panel.close, panel.volume):
        digest.update(str(frame.shape).encode())
        digest.update(
            pd.util.hash_pandas_object(frame, index=True).to_numpy().tobytes()
        )
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Combined panel cache
# ---------------------------------------------------------------------------
def save_panel(panel: Panel, cfg: Config) -> None:
    root = Path(DATA_DIR) / "panel"
    root.mkdir(parents=True, exist_ok=True)
    panel.close.to_parquet(root / "close.parquet")
    panel.volume.to_parquet(root / "volume.parquet")
    metadata = {
        "sha256": panel_hash(panel),
        "rows": int(panel.close.shape[0]),
        "tickers": int(panel.close.shape[1]),
        "start": str(panel.dates[0].date()),
        "end": str(panel.dates[-1].date()),
        "created_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2))


def load_panel(cfg: Config, refresh: bool = False, verbose: bool = True) -> Panel:
    """Load the validated panel, downloading only if the cache is absent."""
    root = Path(DATA_DIR) / "panel"
    close_path = root / "close.parquet"
    volume_path = root / "volume.parquet"
    if close_path.exists() and volume_path.exists() and not refresh:
        panel = Panel(pd.read_parquet(close_path), pd.read_parquet(volume_path))
        validate(panel)
        if not (root / "metadata.json").exists():
            save_panel(panel, cfg)
        if verbose:
            print(
                f"  cached panel: {panel.close.shape[0]} days x {panel.close.shape[1]} tickers"
            )
        return panel

    panel = fetch_panel(cfg, force=refresh, verbose=verbose)
    save_panel(panel, cfg)
    return panel
