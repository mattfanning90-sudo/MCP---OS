"""Strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """A strategy scores each ticker independently over time.

    Scores are in [-1, 1]: positive means attractive to hold long,
    zero or negative means stand aside (microfish is long-only).
    """

    name: str = "strategy"

    @abstractmethod
    def score(self, ohlcv: pd.DataFrame) -> pd.Series:
        """Return a score series aligned to the input's date index.

        `ohlcv` has columns Open, High, Low, Close, Volume. Scores must
        only use information available at each bar's close (no lookahead).
        """

    def score_universe(self, history: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Score every ticker; returns wide DataFrame (date x ticker)."""
        scores = {t: self.score(df) for t, df in history.items()}
        return pd.DataFrame(scores).sort_index()
