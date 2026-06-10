"""Generate today's signals: ranked scores and target portfolio."""

from __future__ import annotations

import pandas as pd

from .config import Config
from .portfolio import target_weights, universe_vols
from .strategies.base import Strategy


def latest_signals(
    history: dict[str, pd.DataFrame],
    strategy: Strategy,
    cfg: Config,
) -> pd.DataFrame:
    """Score the universe as of the latest bar and build the target book.

    Returns a DataFrame indexed by ticker with columns:
    score, ann_vol, weight, dollars (based on cfg.initial_cash).
    """
    scores = strategy.score_universe(history)
    vols = universe_vols(history, cfg.vol_lookback)
    if scores.empty:
        return pd.DataFrame(columns=["score", "ann_vol", "weight", "dollars"])

    as_of = scores.index[-1]
    last_scores = scores.loc[as_of]
    last_vols = vols.reindex(scores.index).loc[as_of]

    weights = target_weights(last_scores, last_vols, cfg)

    book = pd.DataFrame({"score": last_scores, "ann_vol": last_vols})
    book["weight"] = weights.reindex(book.index).fillna(0.0)
    book["dollars"] = (book["weight"] * cfg.initial_cash).round(2)
    book = book.dropna(subset=["score"]).sort_values("score", ascending=False)
    book.attrs["as_of"] = str(as_of.date())
    return book
