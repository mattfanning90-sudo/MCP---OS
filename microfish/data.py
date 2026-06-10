"""Market data layer: yfinance download with local CSV caching."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / f"{ticker.replace('/', '_')}.csv"


def _load_cached(path: Path, max_age_hours: float) -> pd.DataFrame | None:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > max_age_hours * 3600:
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df if not df.empty else None


def fetch_history(
    tickers: list[str],
    start: str,
    end: str | None = None,
    cache_dir: str = ".microfish_cache",
    max_cache_age_hours: float = 12.0,
) -> dict[str, pd.DataFrame]:
    """Fetch daily OHLCV history per ticker, with a local CSV cache.

    Returns a dict of ticker -> DataFrame[Open, High, Low, Close, Volume]
    indexed by date. Tickers with no data are omitted.
    """
    import yfinance as yf

    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    out: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for ticker in tickers:
        cached = _load_cached(_cache_path(cache, ticker), max_cache_age_hours)
        if cached is not None and str(cached.index.min().date()) <= start:
            out[ticker] = cached.loc[start:end]
        else:
            missing.append(ticker)

    if missing:
        raw = yf.download(
            missing,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        for ticker in missing:
            try:
                df = raw[ticker] if len(missing) > 1 else raw
            except KeyError:
                continue
            df = df.dropna(how="all")
            if df.empty:
                continue
            df = df[[c for c in OHLCV if c in df.columns]].copy()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.to_csv(_cache_path(cache, ticker))
            out[ticker] = df

    return out


def close_panel(history: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wide DataFrame of close prices: index=date, columns=tickers."""
    closes = {t: df["Close"] for t, df in history.items()}
    panel = pd.DataFrame(closes).sort_index()
    return panel


def default_start_for_signals(lookback_days: int = 400) -> str:
    """Start date giving enough history to warm up all indicators."""
    return str(date.today() - timedelta(days=lookback_days))
