"""Short-term mean reversion within an uptrend.

Buys oversold dips (low RSI(2), negative z-score vs 20-day mean) but only
for names trading above their 200-day average — fading dips in a downtrend
is how small fish get eaten.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy
from .. import indicators as ind


class MeanReversion(Strategy):
    name = "mean_reversion"

    def __init__(
        self,
        rsi_window: int = 2,
        z_window: int = 20,
        trend_window: int = 200,
    ):
        self.rsi_window = rsi_window
        self.z_window = z_window
        self.trend_window = trend_window

    def score(self, ohlcv: pd.DataFrame) -> pd.Series:
        close = ohlcv["Close"]

        rsi2 = ind.rsi(close, self.rsi_window)
        rsi_score = ((50.0 - rsi2) / 50.0).clip(0.0, 1.0)  # 1 = deeply oversold

        z = ind.zscore(close, self.z_window)
        z_score = (-z / 2.0).clip(0.0, 1.0)  # 1 = two sigmas below mean

        dip = 0.5 * rsi_score + 0.5 * z_score

        in_uptrend = (close > ind.sma(close, self.trend_window)).astype(float)
        score = dip * in_uptrend
        score[rsi2.isna() | z.isna() | ind.sma(close, self.trend_window).isna()] = np.nan
        return score.clip(-1.0, 1.0)
