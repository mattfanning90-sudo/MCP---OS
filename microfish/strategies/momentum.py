"""Trend/momentum strategy.

Combines a long-horizon momentum signal (12-1 month return scaled by
volatility) with a trend filter (price above its 200-day average) and a
shorter 50/200 moving-average regime check.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy
from .. import indicators as ind


class Momentum(Strategy):
    name = "momentum"

    def __init__(
        self,
        long_window: int = 252,
        skip_window: int = 21,
        trend_window: int = 200,
        fast_window: int = 50,
    ):
        self.long_window = long_window
        self.skip_window = skip_window
        self.trend_window = trend_window
        self.fast_window = fast_window

    def score(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["Close"]

        # 12-1 momentum: return from t-252 to t-21, skipping the most
        # recent month (which tends to mean-revert).
        mom = close.shift(self.skip_window) / close.shift(self.long_window) - 1.0
        vol = ind.realized_vol(close, 63)
        risk_adj = mom / vol.replace(0.0, np.nan)
        mom_score = np.tanh(risk_adj)

        trend_ok = (close > ind.sma(close, self.trend_window)).astype(float)
        regime_ok = (
            ind.sma(close, self.fast_window) > ind.sma(close, self.trend_window)
        ).astype(float)
        gate = (trend_ok + regime_ok) / 2.0  # 0, 0.5 or 1

        score = mom_score.clip(lower=0.0) * gate
        score[mom_score.isna() | vol.isna()] = np.nan
        return score.clip(-1.0, 1.0)
