import numpy as np
import pandas as pd

from microfish import indicators as ind


def test_sma_known_values():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = ind.sma(s, 3)
    assert np.isnan(out.iloc[0]) and np.isnan(out.iloc[1])
    assert out.iloc[2] == 2.0
    assert out.iloc[4] == 4.0


def test_rsi_bounds_and_direction():
    up = pd.Series(np.linspace(100, 200, 50))
    down = pd.Series(np.linspace(200, 100, 50))
    rsi_up = ind.rsi(up, 14).iloc[-1]
    rsi_down = ind.rsi(down, 14).iloc[-1]
    assert rsi_up > 90  # monotonic gains -> RSI near 100
    assert rsi_down < 10
    mixed = pd.Series(100 + np.sin(np.arange(100)))
    vals = ind.rsi(mixed, 14).dropna()
    assert ((vals >= 0) & (vals <= 100)).all()


def test_atr_positive_and_warmup():
    n = 50
    close = pd.Series(100 + np.cumsum(np.random.default_rng(0).normal(0, 1, n)))
    high, low = close + 1, close - 1
    out = ind.atr(high, low, close, 14)
    assert out.iloc[:13].isna().all()
    assert (out.dropna() > 0).all()


def test_zscore_centering():
    rng = np.random.default_rng(1)
    s = pd.Series(rng.normal(100, 5, 500))
    z = ind.zscore(s, 20).dropna()
    assert abs(z.mean()) < 0.2
    spike = s.copy()
    spike.iloc[-1] = s.iloc[-1] + 50
    assert ind.zscore(spike, 20).iloc[-1] > 3
