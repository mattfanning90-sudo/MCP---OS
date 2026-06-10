"""Portfolio construction: score -> target weights with risk controls."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from . import indicators as ind


def target_weights(scores: pd.Series, vols: pd.Series, cfg: Config) -> pd.Series:
    """Convert one day's scores into long-only target weights.

    - Drop names below the entry threshold.
    - Keep the top `max_positions` by score.
    - Size inversely to volatility (riskier names get less), scaled by score.
    - Cap each position at `max_weight`; never lever up (sum <= 1).
    """
    scores = scores.dropna()
    vols = vols.reindex(scores.index)

    eligible = scores[scores >= cfg.entry_threshold]
    if eligible.empty:
        return pd.Series(dtype=float)

    picks = eligible.nlargest(cfg.max_positions)
    pick_vols = vols.reindex(picks.index)
    # Fall back to median vol when missing so a gap doesn't inflate a position.
    pick_vols = pick_vols.fillna(pick_vols.median()).replace(0.0, np.nan)
    pick_vols = pick_vols.fillna(pick_vols.median() if pick_vols.notna().any() else 1.0)

    raw = picks / pick_vols
    weights = raw / raw.sum()
    weights = weights.clip(upper=cfg.max_weight)
    # Don't renormalize after capping: excess stays in cash by design.
    return weights


def universe_vols(history: dict[str, pd.DataFrame], window: int = 20) -> pd.DataFrame:
    """Annualized realized vol per ticker (date x ticker)."""
    vols = {t: ind.realized_vol(df["Close"], window) for t, df in history.items()}
    return pd.DataFrame(vols).sort_index()
