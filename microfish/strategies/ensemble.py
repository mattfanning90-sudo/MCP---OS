"""Weighted ensemble of sub-strategies with volume confirmation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy
from .momentum import Momentum
from .mean_reversion import MeanReversion
from .. import indicators as ind


class Ensemble(Strategy):
    name = "ensemble"

    def __init__(
        self,
        momentum_weight: float = 0.6,
        mean_reversion_weight: float = 0.4,
        volume_window: int = 20,
    ):
        total = momentum_weight + mean_reversion_weight
        self.momentum_weight = momentum_weight / total
        self.mean_reversion_weight = mean_reversion_weight / total
        self.volume_window = volume_window
        self.momentum = Momentum()
        self.mean_reversion = MeanReversion()

    def score(self, ohlcv: pd.DataFrame) -> pd.Series:
        mom = self.momentum.score(ohlcv)
        rev = self.mean_reversion.score(ohlcv)
        combined = self.momentum_weight * mom + self.mean_reversion_weight * rev

        # Volume confirmation: scale conviction down to 70% when volume is
        # drying up relative to its 20-day average (illiquidity penalty).
        volume = ohlcv["Volume"].astype(float)
        vol_ratio = volume / ind.sma(volume, self.volume_window)
        confirm = vol_ratio.clip(0.5, 1.0).fillna(1.0) * 0.6 + 0.4  # in [0.7, 1.0]

        return (combined * confirm).clip(-1.0, 1.0)
