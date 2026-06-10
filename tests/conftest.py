"""Synthetic OHLCV fixtures — tests never hit the network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(closes: np.ndarray, start: str = "2020-01-01") -> pd.DataFrame:
    """Build a plausible OHLCV frame around a given close series."""
    idx = pd.bdate_range(start, periods=len(closes))
    close = pd.Series(closes, index=idx)
    return pd.DataFrame({
        "Open": close.shift(1).fillna(close.iloc[0]),
        "High": close * 1.01,
        "Low": close * 0.99,
        "Close": close,
        "Volume": np.full(len(closes), 1_000_000.0),
    })


@pytest.fixture
def uptrend() -> pd.DataFrame:
    n = 400
    closes = 100.0 * np.exp(np.linspace(0, 0.6, n))  # smooth ~82% rise
    return make_ohlcv(closes)


@pytest.fixture
def downtrend() -> pd.DataFrame:
    n = 400
    closes = 100.0 * np.exp(np.linspace(0, -0.6, n))
    return make_ohlcv(closes)


@pytest.fixture
def flat() -> pd.DataFrame:
    return make_ohlcv(np.full(400, 100.0))


@pytest.fixture
def universe(uptrend, downtrend, flat) -> dict[str, pd.DataFrame]:
    return {"UP.AX": uptrend, "DOWN.AX": downtrend, "FLAT.AX": flat}
